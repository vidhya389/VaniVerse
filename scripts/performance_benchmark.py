"""
Performance benchmarking tool for VaniVerse

Measures voice loop latency, parallel API optimization, and network performance.
"""

import boto3
import time
import json
import uuid
import statistics
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any


class PerformanceBenchmark:
    """Performance benchmarking for VaniVerse"""
    
    def __init__(self, region='ap-south-1', environment='staging'):
        self.region = region
        self.environment = environment
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.s3_client = boto3.client('s3', region_name=region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        
        self.function_name = f'vaniverse-orchestrator-{environment}'
        self.input_bucket = f'vaniverse-audio-input-{environment}'
        
        self.results = []
    
    def upload_test_audio(self, farmer_id: str, language: str = 'hi-IN') -> str:
        """Upload test audio file to S3"""
        audio_key = f'test-audio/{uuid.uuid4()}.wav'
        
        # Create minimal test audio data (placeholder)
        test_audio = b'RIFF' + b'\x00' * 100  # Minimal WAV header
        
        # Upload with metadata
        self.s3_client.put_object(
            Bucket=self.input_bucket,
            Key=audio_key,
            Body=test_audio,
            Metadata={
                'farmerId': farmer_id,
                'language': language,
                'gpsLatitude': '28.6139',
                'gpsLongitude': '77.2090'
            }
        )
        
        return audio_key
    
    def invoke_lambda_direct(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke Lambda function directly"""
        response = self.lambda_client.invoke(
            FunctionName=self.function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(event)
        )
        
        result = json.loads(response['Payload'].read())
        return result
    
    def measure_voice_loop_latency(self, num_iterations: int = 10) -> Dict[str, float]:
        """
        Measure voice loop latency over multiple iterations
        
        Target: < 6 seconds
        """
        print(f"Measuring voice loop latency ({num_iterations} iterations)...")
        
        latencies = []
        
        for i in range(num_iterations):
            farmer_id = f'PERF-TEST-{uuid.uuid4()}'
            
            # Create test event
            event = {
                'Records': [{
                    's3': {
                        'bucket': {'name': self.input_bucket},
                        'object': {
                            'key': f'test-audio/{uuid.uuid4()}.wav',
                            'size': 50000
                        }
                    }
                }],
                'metadata': {
                    'farmerId': farmer_id,
                    'language': 'hi-IN',
                    'gpsLatitude': '28.6139',
                    'gpsLongitude': '77.2090'
                }
            }
            
            # Measure execution time
            start_time = time.time()
            try:
                result = self.invoke_lambda_direct(event)
                latency = time.time() - start_time
                
                if result.get('statusCode') == 200:
                    latencies.append(latency)
                    print(f"  Iteration {i+1}: {latency:.2f}s")
                else:
                    print(f"  Iteration {i+1}: Failed with status {result.get('statusCode')}")
            except Exception as e:
                print(f"  Iteration {i+1}: Error - {e}")
        
        if not latencies:
            return {'error': 'No successful iterations'}
        
        results = {
            'min': min(latencies),
            'max': max(latencies),
            'mean': statistics.mean(latencies),
            'median': statistics.median(latencies),
            'p95': statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies),
            'p99': statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else max(latencies),
            'samples': len(latencies),
            'target_met': max(latencies) < 6.0
        }
        
        print(f"\n  Results:")
        print(f"    Min:    {results['min']:.2f}s")
        print(f"    Max:    {results['max']:.2f}s")
        print(f"    Mean:   {results['mean']:.2f}s")
        print(f"    Median: {results['median']:.2f}s")
        print(f"    P95:    {results['p95']:.2f}s")
        print(f"    Target (<6s): {'✓ MET' if results['target_met'] else '✗ NOT MET'}")
        
        self.results.append({
            'test': 'voice_loop_latency',
            'timestamp': datetime.now().isoformat(),
            'results': results
        })
        
        return results
    
    def measure_parallel_api_performance(self) -> Dict[str, Any]:
        """
        Measure parallel API call optimization
        
        Validates that context retrieval happens in parallel
        """
        print("Measuring parallel API call performance...")
        
        # This would require instrumentation in the Lambda function
        # For now, we'll measure overall latency as a proxy
        
        event = {
            'Records': [{
                's3': {
                    'bucket': {'name': self.input_bucket},
                    'object': {
                        'key': f'test-audio/{uuid.uuid4()}.wav',
                        'size': 50000
                    }
                }
            }],
            'metadata': {
                'farmerId': f'PERF-TEST-{uuid.uuid4()}',
                'language': 'hi-IN',
                'gpsLatitude': '28.6139',
                'gpsLongitude': '77.2090'
            }
        }
        
        start_time = time.time()
        result = self.invoke_lambda_direct(event)
        total_time = time.time() - start_time
        
        # Check CloudWatch logs for parallel execution evidence
        # This is a simplified check
        results = {
            'total_time': total_time,
            'status': result.get('statusCode'),
            'parallel_optimization': total_time < 4.0  # If parallel, should be faster
        }
        
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Parallel optimization: {'✓ LIKELY' if results['parallel_optimization'] else '✗ UNLIKELY'}")
        
        self.results.append({
            'test': 'parallel_api_performance',
            'timestamp': datetime.now().isoformat(),
            'results': results
        })
        
        return results
    
    def measure_concurrent_load(self, num_concurrent: int = 10) -> Dict[str, Any]:
        """
        Measure system performance under concurrent load
        """
        print(f"Measuring concurrent load ({num_concurrent} concurrent requests)...")
        
        def invoke_single():
            event = {
                'Records': [{
                    's3': {
                        'bucket': {'name': self.input_bucket},
                        'object': {
                            'key': f'test-audio/{uuid.uuid4()}.wav',
                            'size': 50000
                        }
                    }
                }],
                'metadata': {
                    'farmerId': f'PERF-TEST-{uuid.uuid4()}',
                    'language': 'hi-IN',
                    'gpsLatitude': '28.6139',
                    'gpsLongitude': '77.2090'
                }
            }
            
            start_time = time.time()
            try:
                result = self.invoke_lambda_direct(event)
                latency = time.time() - start_time
                return {
                    'success': result.get('statusCode') == 200,
                    'latency': latency
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e)
                }
        
        # Execute concurrent requests
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(invoke_single) for _ in range(num_concurrent)]
            results_list = [future.result() for future in as_completed(futures)]
        total_time = time.time() - start_time
        
        # Analyze results
        successful = [r for r in results_list if r.get('success')]
        failed = [r for r in results_list if not r.get('success')]
        
        latencies = [r['latency'] for r in successful]
        
        results = {
            'total_requests': num_concurrent,
            'successful': len(successful),
            'failed': len(failed),
            'total_time': total_time,
            'throughput': num_concurrent / total_time,
            'avg_latency': statistics.mean(latencies) if latencies else 0,
            'max_latency': max(latencies) if latencies else 0
        }
        
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Successful: {results['successful']}/{results['total_requests']}")
        print(f"  Throughput: {results['throughput']:.2f} req/s")
        print(f"  Avg latency: {results['avg_latency']:.2f}s")
        print(f"  Max latency: {results['max_latency']:.2f}s")
        
        self.results.append({
            'test': 'concurrent_load',
            'timestamp': datetime.now().isoformat(),
            'results': results
        })
        
        return results
    
    def measure_network_conditions(self) -> Dict[str, Any]:
        """
        Test performance under various network conditions
        """
        print("Testing network condition handling...")
        
        # Test with different file sizes (simulating bandwidth)
        test_cases = [
            {'size': 30000, 'label': 'Low bandwidth (2G)'},
            {'size': 50000, 'label': 'Normal bandwidth (3G)'},
            {'size': 100000, 'label': 'High bandwidth (4G)'}
        ]
        
        results_by_condition = []
        
        for test_case in test_cases:
            print(f"  Testing: {test_case['label']}")
            
            event = {
                'Records': [{
                    's3': {
                        'bucket': {'name': self.input_bucket},
                        'object': {
                            'key': f'test-audio/{uuid.uuid4()}.wav',
                            'size': test_case['size']
                        }
                    }
                }],
                'metadata': {
                    'farmerId': f'PERF-TEST-{uuid.uuid4()}',
                    'language': 'hi-IN',
                    'gpsLatitude': '28.6139',
                    'gpsLongitude': '77.2090',
                    'bandwidth': 80 if test_case['size'] < 40000 else 200
                }
            }
            
            start_time = time.time()
            try:
                result = self.invoke_lambda_direct(event)
                latency = time.time() - start_time
                
                results_by_condition.append({
                    'condition': test_case['label'],
                    'latency': latency,
                    'success': result.get('statusCode') == 200
                })
                
                print(f"    Latency: {latency:.2f}s")
            except Exception as e:
                print(f"    Error: {e}")
                results_by_condition.append({
                    'condition': test_case['label'],
                    'error': str(e),
                    'success': False
                })
        
        results = {
            'conditions_tested': len(test_cases),
            'results': results_by_condition
        }
        
        self.results.append({
            'test': 'network_conditions',
            'timestamp': datetime.now().isoformat(),
            'results': results
        })
        
        return results
    
    def get_cloudwatch_metrics(self, hours: int = 1) -> Dict[str, Any]:
        """
        Retrieve CloudWatch metrics for analysis
        """
        print(f"Retrieving CloudWatch metrics (last {hours} hour(s))...")
        
        end_time = datetime.now()
        start_time = datetime.now() - timedelta(hours=hours)
        
        metrics_to_fetch = [
            {'name': 'Duration', 'stat': 'Average'},
            {'name': 'Duration', 'stat': 'Maximum'},
            {'name': 'Errors', 'stat': 'Sum'},
            {'name': 'Throttles', 'stat': 'Sum'},
            {'name': 'ConcurrentExecutions', 'stat': 'Maximum'}
        ]
        
        results = {}
        
        for metric in metrics_to_fetch:
            try:
                response = self.cloudwatch_client.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName=metric['name'],
                    Dimensions=[
                        {'Name': 'FunctionName', 'Value': self.function_name}
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,
                    Statistics=[metric['stat']]
                )
                
                datapoints = response.get('Datapoints', [])
                if datapoints:
                    value = datapoints[0].get(metric['stat'], 0)
                    results[f"{metric['name']}_{metric['stat']}"] = value
                    print(f"  {metric['name']} ({metric['stat']}): {value}")
            except Exception as e:
                print(f"  Error fetching {metric['name']}: {e}")
        
        return results
    
    def generate_report(self, output_file: str = None):
        """Generate performance report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'environment': self.environment,
            'region': self.region,
            'function_name': self.function_name,
            'tests': self.results
        }
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n✓ Report saved to: {output_file}")
        
        return report
    
    def run_all_benchmarks(self):
        """Run all performance benchmarks"""
        print("=" * 80)
        print("VaniVerse Performance Benchmarks")
        print("=" * 80)
        print(f"Environment: {self.environment}")
        print(f"Region: {self.region}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print("=" * 80)
        print()
        
        # Run benchmarks
        self.measure_voice_loop_latency(num_iterations=10)
        print()
        
        self.measure_parallel_api_performance()
        print()
        
        self.measure_concurrent_load(num_concurrent=5)
        print()
        
        self.measure_network_conditions()
        print()
        
        # Generate report
        report_file = f'performance_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        self.generate_report(report_file)
        
        print()
        print("=" * 80)
        print("✓ All benchmarks completed")
        print("=" * 80)


def main():
    """Main benchmark runner"""
    import argparse
    from datetime import timedelta
    
    parser = argparse.ArgumentParser(description="Run VaniVerse performance benchmarks")
    parser.add_argument(
        '--environment',
        default='staging',
        help='Environment to test (staging/production)'
    )
    parser.add_argument(
        '--region',
        default='ap-south-1',
        help='AWS region'
    )
    parser.add_argument(
        '--test',
        choices=['latency', 'parallel', 'concurrent', 'network', 'all'],
        default='all',
        help='Specific test to run'
    )
    
    args = parser.parse_args()
    
    # Check AWS credentials
    try:
        boto3.client('sts').get_caller_identity()
    except Exception as e:
        print(f"✗ AWS credentials not configured: {e}")
        return 1
    
    # Run benchmarks
    benchmark = PerformanceBenchmark(
        region=args.region,
        environment=args.environment
    )
    
    if args.test == 'all':
        benchmark.run_all_benchmarks()
    elif args.test == 'latency':
        benchmark.measure_voice_loop_latency()
    elif args.test == 'parallel':
        benchmark.measure_parallel_api_performance()
    elif args.test == 'concurrent':
        benchmark.measure_concurrent_load()
    elif args.test == 'network':
        benchmark.measure_network_conditions()
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
